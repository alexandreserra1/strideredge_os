"""analytics/risk_assessor.py — escolhe o avaliador de risco: TREINADO ou PRIOR da literatura.

Regra honesta (AI-STRATEGY: prior → treinado quando há dado): o Random Forest só entra quando há
casos REAIS suficientes pra treinar honesto. Abaixo do limiar (ou sem lesionados reais), fica no
score da literatura. NUNCA serve modelo sintético como risco real de usuário — dados sintéticos
(`synthetic-…`) são EXCLUÍDOS da decisão. Ambos têm a mesma interface (drop-in), então o coach só
chama `assessor(metrics, profile, history)` sem saber qual é.
"""

from typing import Callable

from analytics.injury_risk import assess
from analytics.injury_model import RiskModel
from analytics.injury_bayes import BayesianRiskModel
from analytics.injury_dataset import build_training_set
from analytics.injury_seed import SYNTHETIC_PREFIX

# Abaixo disto, treinar um RF é instável/overfit — fica no regime prior/bayes (mais honesto).
MIN_REAL_CASES = 40
MIN_REAL_POSITIVES = 10

_cache: dict = {"model": None, "n": None, "bayes": None, "bayes_n": None, "report": None}


def _real_cases() -> list:
    """Exemplos rotulados de usuários REAIS (exclui os sintéticos semeados)."""
    return [e for e in build_training_set()
            if not str(e["user_id"]).startswith(SYNTHETIC_PREFIX)]


def _regime_for(cases: list) -> str:
    """Qual nível o volume de dado REAL habilita: prior (0), bayes (pouco), treinado (suficiente).
    Fonte única da decisão — `current_assessor` e `risk_regime` leem daqui pra nunca divergirem."""
    positives = sum(e["label"] for e in cases)
    if not cases:
        return "prior"
    if len(cases) < MIN_REAL_CASES or positives < MIN_REAL_POSITIVES:
        return "bayes"
    return "trained"


def current_assessor() -> Callable:
    """Avaliador de risco a usar AGORA, pela quantidade de dado REAL disponível (progressão honesta
    literatura → bayes → treinado). Cacheia por volume de dados (não recomputa a cada chamada):
      - 0 caso real           → `assess` (prior da literatura puro);
      - poucos casos (< RF)   → `BayesianRiskModel` — refina o prior online, funciona com pouco dado;
      - dado suficiente       → `RiskModel` (Random Forest treinado)."""
    cases = _real_cases()
    regime = _regime_for(cases)
    if regime == "prior":
        return assess                           # sem outcome real → é o prior da literatura
    if regime == "bayes":
        if _cache["bayes"] is None or _cache["bayes_n"] != len(cases):
            _cache["bayes"] = BayesianRiskModel().partial_fit(cases)
            _cache["bayes_n"] = len(cases)
        return _cache["bayes"].predict
    if _cache["model"] is None or _cache["n"] != len(cases):
        model = RiskModel()
        _cache["report"] = model.train(cases)   # guarda o boletim (PR-AUC) p/ o risk_regime
        _cache["model"], _cache["n"] = model, len(cases)
    return _cache["model"].predict


def risk_regime() -> dict:
    """Estado HONESTO do avaliador de risco: qual nível está ativo e POR QUÊ (nº de casos reais +
    positivos vs. os limiares). Se treinado, inclui o boletim (PR-AUC + tipo de validação).
    Transparência do ciclo que se auto-fecha: enquanto não há outcome real, é o prior CITADO da
    literatura — e isso fica explícito, sem fingir que já 'aprendeu' com o atleta."""
    cases = _real_cases()
    regime = _regime_for(cases)
    out = {
        "regime": regime,   # 'prior' | 'bayes' | 'trained'
        "real_cases": len(cases),
        "real_positives": sum(e["label"] for e in cases),
        "min_cases": MIN_REAL_CASES,
        "min_positives": MIN_REAL_POSITIVES,
    }
    if regime == "trained":
        current_assessor()                      # garante que o modelo (e o boletim) estão no cache
        out["model_report"] = _cache.get("report")
    return out
