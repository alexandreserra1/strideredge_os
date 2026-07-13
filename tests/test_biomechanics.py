"""Testa os alvos personalizados + diagnóstico de gap (aritmética pura, sem LLM)."""

from analytics.biomechanics import ideal_targets, diagnose


def test_cadencia_alvo_escala_com_altura():
    base = ideal_targets()
    assert base["cadence_spm"]["lo"] == 170.0
    alto = ideal_targets({"height_cm": 185})   # +10cm -> piso ~3 spm menor
    assert alto["cadence_spm"]["lo"] < base["cadence_spm"]["lo"]
    assert abs(alto["cadence_spm"]["lo"] - 167.0) < 0.1


def test_diagnose_ordena_por_severidade_e_ignora_dentro_da_faixa():
    t = ideal_targets()
    metrics = {
        "cadence_spm": 150,               # bem abaixo do piso (170) -> desvio grande
        "vertical_oscillation_pct": 9,    # pouco acima de 8 -> desvio pequeno
        "asymmetry_pct": 5,               # dentro (<10) -> ignorado
        "trunk_lean_deg": 8,              # dentro (5-14) -> ignorado
    }
    devs = diagnose(metrics, t)
    metricas = [d["metric"] for d in devs]
    assert "asymmetry_pct" not in metricas and "trunk_lean_deg" not in metricas
    assert devs[0]["metric"] == "cadence_spm"     # pior desvio primeiro
    assert devs[0]["side"] == "baixo"
    assert all("source" in d and "query" in d for d in devs)


def test_forma_perfeita_sem_desvios():
    t = ideal_targets()
    metrics = {"cadence_spm": 180, "ground_contact_ms": 230, "vertical_oscillation_pct": 6,
               "knee_contact_deg": 160, "trunk_lean_deg": 8, "asymmetry_pct": 4}
    assert diagnose(metrics, t) == []
