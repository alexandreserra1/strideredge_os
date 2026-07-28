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
from analytics.injury_taxonomy import DIAGNOSES, factors_for, is_mapped, valid_diagnosis

_FACTOR_KEYS = tuple(ideal_targets().keys())


def injury_history(user_id: str) -> dict:
    """Histórico de lesão do atleta -> `{factors, diagnoses, regions}`. `factors` = união dos
    fatores biomecânicos que a taxonomia liga às lesões já reportadas (reusa `factors_for`). É o
    que `assess`/`ideal_targets` consomem p/ sensibilizar o risco (lesão prévia = preditor #1)."""
    if not user_id:
        return {"factors": [], "diagnoses": [], "regions": []}
    rows = get_connection().execute(
        "SELECT DISTINCT diagnosis, region FROM injury_reports WHERE user_id = ?", [user_id]).fetchall()
    diagnoses = {d for d, _ in rows if d}
    regions = {r for _, r in rows if r}
    factors = set()
    for dx in diagnoses:
        factors |= set(factors_for(dx))
    return {"factors": sorted(factors), "diagnoses": sorted(diagnoses), "regions": sorted(regions)}


def _ideal_str(t: dict) -> str:
    """Faixa ideal em texto p/ a UI (mesma direção do diagnose)."""
    if t["dir"] == "lower_better":
        return f"≤ {t['hi']:g}{t['unit']}"
    if t["dir"] == "higher_better":
        return f"≥ {t['lo']:g}{t['unit']}"
    return f"{t['lo']:g}–{t['hi']:g}{t['unit']}"


def injury_retrospective(user_id: str, diagnosis: str, onset, window_weeks: int = 8) -> dict:
    """RETROSPECTO HONESTO da lesão: cruza os fatores que a LITERATURA liga ao diagnóstico com as
    análises de forma do atleta na janela ANTES do onset. É face-validity do prior contra o outcome
    REAL do próprio atleta — NÃO é prova de causa nem diagnóstico. Reusa `_analyses_before`,
    `_mean_features`, `diagnose` e a taxonomia. Degrada gracioso: sem diagnóstico mapeado ou sem
    análises no período → devolve status próprio + caveat, nunca inventa sinal."""
    dx = DIAGNOSES.get(diagnosis)
    if not dx or not dx.get("source"):
        return {"status": "unmapped", "signals": [], "analyses_before": 0,
                "caveat": "Sem um diagnóstico ligado à literatura, não dá pra cruzar com a sua forma."}
    base = {"diagnosis": diagnosis, "diagnosis_label": dx["label"], "source": dx["source"],
            "window_weeks": window_weeks}
    metrics_list = _analyses_before(get_connection(), user_id, onset, window_weeks)
    if not metrics_list:
        return {**base, "status": "no_history", "signals": [], "analyses_before": 0,
                "caveat": "Você não tem análises de forma no período antes desta lesão pra comparar. "
                          "Filme suas corridas daqui pra frente — aí a gente consegue cruzar."}
    feats = _mean_features(metrics_list)
    targets = ideal_targets()
    signals = []
    for f in dx["factors"]:
        t = targets.get(f)
        if t is None:
            continue
        v = feats.get(f)
        if v is None:
            signals.append({"metric": f, "label": t["label"], "present": None,
                            "note": "não foi medido nas suas capturas desse período"})
            continue
        deviated = bool(diagnose({f: v}, {f: t}))   # o MESMO motor de desvio (nada de limiar paralelo)
        signals.append({"metric": f, "label": t["label"], "present": deviated,
                        "value": v, "unit": t["unit"], "ideal": _ideal_str(t)})
    return {**base, "status": "ok", "analyses_before": len(metrics_list), "signals": signals,
            "caveat": "Isto é uma associação da literatura (não prova que causou), cruzada com um "
                      "retrospecto das suas próprias capturas — não substitui avaliação profissional."}


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
        "WHERE onset_date IS NOT NULL AND user_id IS NOT NULL "
        "AND diagnosis IS NOT NULL AND training_approved = TRUE").fetchall()
    out = []
    for user_id, dx, region, onset in injuries:
        # rótulo tem que estar no vocabulário vigente (dx de versão antiga da taxonomia não treina)
        if not valid_diagnosis(dx):
            continue
        feats = _mean_features(_analyses_before(con, user_id, onset, window_weeks))
        if feats:
            out.append({"user_id": str(user_id), "label_dx": dx, "label_region": region,
                        "features": feats, "n_analyses": len(_analyses_before(con, user_id, onset, window_weeks))})
    return out


def build_training_set(window_weeks: int = 8) -> list:
    """Dataset BINÁRIO p/ o RiskModel: positivos (lesionados, features médias PRÉ-onset, label 1) +
    negativos (atletas com análise e SEM lesão, features médias, label 0). É o `build_dataset`
    fechado com a classe negativa — sem negativo não dá pra treinar lesionado-vs-saudável."""
    con = get_connection()
    out = []
    # positivos: lesionados com análise na janela anterior
    injuries = con.execute(
        "SELECT user_id, onset_date FROM injury_reports "
        "WHERE onset_date IS NOT NULL AND user_id IS NOT NULL AND diagnosis IS NOT NULL "
        "AND training_approved = TRUE").fetchall()
    injured_users = set()
    for user_id, onset in injuries:
        injured_users.add(str(user_id))
        feats = _mean_features(_analyses_before(con, user_id, onset, window_weeks))
        if feats:
            out.append({"user_id": str(user_id), "features": feats, "label": 1})
    # Negativos precisam de atleta sem NENHUMA lesão relatada: um outcome ainda pendente é
    # desconhecido, não pode virar artificialmente saudável só porque não foi aprovado.
    reported_users = {str(r[0]) for r in con.execute(
        "SELECT DISTINCT user_id FROM injury_reports WHERE user_id IS NOT NULL").fetchall()}
    rows = con.execute(
        "SELECT DISTINCT user_id FROM form_analyses WHERE user_id IS NOT NULL AND status = 'done'"
    ).fetchall()
    for (user_id,) in rows:
        if str(user_id) in injured_users or str(user_id) in reported_users:
            continue
        metrics = [json.loads(r[0]) for r in con.execute(
            "SELECT metrics FROM form_analyses WHERE user_id = ? AND status = 'done' "
            "AND metrics IS NOT NULL", [user_id]).fetchall()]
        feats = _mean_features(metrics)
        if feats:
            out.append({"user_id": str(user_id), "features": feats, "label": 0})
    return out


def validate_literature_model(window_weeks: int = 8) -> dict:
    """Face-validity do modelo de risco da literatura contra outcome real: pra cada lesão MAPEADA,
    as análises anteriores flaguearam os fatores que a taxonomia liga a ela?"""
    con = get_connection()
    targets = ideal_targets()
    injuries = con.execute(
        "SELECT user_id, diagnosis, onset_date FROM injury_reports "
        "WHERE onset_date IS NOT NULL AND user_id IS NOT NULL AND training_approved = TRUE").fetchall()
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
