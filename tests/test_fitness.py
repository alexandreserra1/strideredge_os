"""Testes do preditor de prova (Riegel) e tendência de fitness."""

from analytics.fitness import RunningFitness


# --- Funções puras (sem banco) ---

def test_riegel_dobra_distancia():
    # 20min nos 5k → 10k: t2 = 1200 * 2^1.06 ≈ 2502s (~41:42), não o dobro ingênuo (2400s).
    t2 = RunningFitness.riegel(1200, 5000, 10000)
    assert 2490 < t2 < 2510
    assert t2 > 2400  # Riegel penaliza a distância maior


def test_riegel_mesma_distancia_e_identidade():
    assert RunningFitness.riegel(1500, 5000, 5000) == 1500


def test_trend_label():
    assert RunningFitness.trend_label([10, 11, 12, 13]) == "melhorando"
    assert RunningFitness.trend_label([13, 12, 11, 10]) == "caindo"
    assert RunningFitness.trend_label([10, 10, 10, 10]) == "estavel"
    assert RunningFitness.trend_label([10, 11]) == "dados insuficientes"


# --- Integração com o banco sintético (conftest) ---

def test_race_predictions_da_referencia_real():
    res = RunningFitness().race_predictions()
    assert res["reference"] is not None
    labels = {p["race"] for p in res["predictions"]}
    assert {"5k", "10k", "21k (meia)", "42k (maratona)"} <= labels
    # tempos crescem com a distância
    by = {p["race"]: p["time_s"] for p in res["predictions"]}
    assert by["5k"] < by["10k"] < by["42k (maratona)"]
    assert all(p["time_s"] > 0 for p in res["predictions"])


def test_efficiency_trend_tem_pontos_e_rotulo():
    res = RunningFitness().efficiency_trend()
    assert "trend" in res
    assert all("efficiency" in p and p["efficiency"] > 0 for p in res["points"])
