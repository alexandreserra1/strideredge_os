"""analytics/injury_quality.py — filtro de qualidade: nenhum dado ruidoso treina o modelo.

Constituição §7 ("dado validado, nunca chutado") aplicada ao ML. TODO dataset — sintético, de
usuário, ou externo — passa por `clean` antes de treinar. Trata três ruídos reais:
  - valor FISIOLOGICAMENTE impossível (ex.: queda pélvica negativa, cadência 500) → clipa pro
    limite plausível (é ruído de cauda/medição, não sinal — descartar a linha jogaria fora o resto).
  - linha quase vazia (features de menos pra ser exemplo confiável) → descarta.
  - duplicata exata → descarta (não infla o modelo com repetição).
Devolve os dados limpos + um RELATÓRIO do que mexeu (transparência, não silencioso)."""

import json

# Limites FISIOLÓGICOS plausíveis por fator (mais largos que o "ideal" — lesionado excede o ideal,
# mas não a fisiologia). Fora disto = ruído de medição/corrupção, não biomecânica real.
PLAUSIBLE = {
    "cadence_spm": (120.0, 230.0),
    "ground_contact_ms": (100.0, 400.0),
    "vertical_oscillation_pct": (2.0, 20.0),
    "knee_contact_deg": (110.0, 180.0),
    "trunk_lean_deg": (0.0, 30.0),
    "asymmetry_pct": (0.0, 50.0),
    "pelvic_drop_deg": (0.0, 30.0),
    "knee_valgus_deg": (0.0, 30.0),
}
_MIN_FEATURES = 3   # menos que isso não é um exemplo confiável


def _clip_row(features: dict) -> tuple:
    """Clipa cada fator ao limite plausível. Devolve (features_limpas, nº de valores clipados)."""
    clipped, clean = 0, {}
    for k, v in features.items():
        bounds = PLAUSIBLE.get(k)
        if bounds and v is not None:
            lo, hi = bounds
            new = min(max(v, lo), hi)
            if new != v:
                clipped += 1
            clean[k] = round(new, 2)
        else:
            clean[k] = v
    return clean, clipped


def clean(examples: list) -> tuple:
    """Filtra dados ruidosos. Devolve (limpos, relatório). Relatório = o que foi clipado/descartado."""
    out, seen = [], set()
    clipped_values, dropped_sparse, dropped_dupes = 0, 0, 0
    for ex in examples:
        feats = {k: v for k, v in ex["features"].items() if v is not None}
        if len(feats) < _MIN_FEATURES:
            dropped_sparse += 1
            continue
        clean_feats, clipped = _clip_row(feats)
        clipped_values += clipped
        key = json.dumps(clean_feats, sort_keys=True) + f"|{ex.get('label')}"
        if key in seen:
            dropped_dupes += 1
            continue
        seen.add(key)
        out.append({**ex, "features": clean_feats})
    report = {
        "n_in": len(examples), "n_out": len(out), "clipped_values": clipped_values,
        "dropped_sparse": dropped_sparse, "dropped_duplicates": dropped_dupes,
    }
    return out, report
