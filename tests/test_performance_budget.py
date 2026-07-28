"""Guarda de PERFORMANCE hermético — regressão ALGORÍTMICA, não benchmark de modelo.

Não mede pose/GPU/vídeo (isso é E2E ao vivo). Roda as funções determinísticas pesadas do caminho
crítico (diagnose, assess, sanitize_metrics, build_plan) sobre entradas grandes/repetidas e trava
um orçamento de tempo FOLGADO. Objetivo: pegar um O(n²) acidental, um loop que passou a varrer tudo,
uma regressão que multiplica o custo por passada — SEM ser flaky. A margem é generosa de propósito
(CI compartilhado é lento); só dispara se algo ficar ORDENS de grandeza pior, não com jitter normal.
"""

import time

from analytics.biomechanics import ideal_targets, diagnose
from analytics.injury_risk import assess
from analytics.injury_quality import sanitize_metrics
from analytics.training_plan import build_plan

# métricas com TODOS os fatores fora do ideal (caminho mais caro: todo desvio vira contribuição,
# by_injury decompõe todas as lesões, build_plan sequencia todos os exercícios).
_METRICS = {
    "cadence_spm": 150.0, "ground_contact_ms": 300.0, "vertical_oscillation_pct": 12.0,
    "knee_contact_deg": 178.0, "trunk_lean_deg": 20.0, "asymmetry_pct": 15.0,
    "pelvic_drop_deg": 15.0, "knee_valgus_deg": 15.0, "reliable": True,
}

_BUDGET_S = 2.0   # orçamento folgado: 5000 iterações de aritmética pura sobem em ms, não segundos.


def _elapsed(fn, n=5000):
    start = time.perf_counter()
    for _ in range(n):
        fn()
    return time.perf_counter() - start


def test_diagnose_sob_orcamento():
    targets = ideal_targets()
    assert _elapsed(lambda: diagnose(_METRICS, targets)) < _BUDGET_S


def test_assess_sob_orcamento():
    # assess embute diagnose + decomposição por lesão — o mais pesado do trio determinístico.
    assert _elapsed(lambda: assess(_METRICS)) < _BUDGET_S


def test_sanitize_metrics_sob_orcamento():
    assert _elapsed(lambda: sanitize_metrics(_METRICS)) < _BUDGET_S


def test_build_plan_sob_orcamento():
    factors = assess(_METRICS)["factors"]
    # plano no teto de semanas (16) — o laço temporal completo, com todos os fatores priorizados.
    assert _elapsed(lambda: build_plan(factors, weeks=16)) < _BUDGET_S


def test_metricas_com_muitos_campos_extras_nao_degrada():
    """Dict inflado com campos que não são fatores (telemetria, metadados): as funções só olham
    as chaves conhecidas — campos extras não podem virar custo linear no total de chaves."""
    inflado = dict(_METRICS)
    for i in range(2000):
        inflado[f"campo_extra_{i}"] = float(i)
    targets = ideal_targets()
    assert _elapsed(lambda: diagnose(inflado, targets), n=2000) < _BUDGET_S
    assert _elapsed(lambda: sanitize_metrics(inflado), n=2000) < _BUDGET_S
