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
from analytics.injury_dataset import build_training_set
from analytics.injury_seed import SYNTHETIC_PREFIX

# Abaixo disto, treinar é instável/overfit — o prior da literatura é mais honesto.
MIN_REAL_CASES = 40
MIN_REAL_POSITIVES = 10

_cache: dict = {"model": None, "n": None}


def _real_cases() -> list:
    """Exemplos rotulados de usuários REAIS (exclui os sintéticos semeados)."""
    return [e for e in build_training_set()
            if not str(e["user_id"]).startswith(SYNTHETIC_PREFIX)]


def current_assessor() -> Callable:
    """Avaliador de risco a usar AGORA. `predict` do treinado se há dado real suficiente; senão
    `assess` da literatura. Cacheia o modelo por volume de dados (não retreina a cada chamada)."""
    cases = _real_cases()
    positives = sum(e["label"] for e in cases)
    if len(cases) < MIN_REAL_CASES or positives < MIN_REAL_POSITIVES:
        return assess
    if _cache["model"] is None or _cache["n"] != len(cases):
        model = RiskModel()
        model.train(cases)
        _cache["model"], _cache["n"] = model, len(cases)
    return _cache["model"].predict
