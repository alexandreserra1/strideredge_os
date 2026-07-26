"""Testa metric_quality + o filtro de confiabilidade em diagnose/FormCoach.plan().

Contrato (ver stride_vision/metrics.rs, gerado por outro agente em paralelo):
- metrics["metric_confidence"]: dict[str, float] 0..1 — fração de frames confiáveis por métrica.
- metrics["metric_cv"]: dict[str, float] — coef. de variação entre passadas (ausente p/ métricas
  de amostra única, ex. cadência).
- Ambos podem estar AUSENTES (dumps antigos/testes) — nesse caso, comportamento IDÊNTICO ao de
  antes desta mudança (regressão coberta abaixo).
"""

from unittest.mock import MagicMock

from analytics.biomechanics import ideal_targets, diagnose, metric_quality
from analytics.form_coach import FormCoach


def test_metric_quality_sem_info_e_none():
    """Sem metric_confidence no dict -> None (sem informação de qualidade), não 0."""
    assert metric_quality({"knee_contact_deg": 160}, "knee_contact_deg") is None


def test_metric_quality_chave_ausente_no_dict_de_confianca_e_none():
    metrics = {"metric_confidence": {"cadence_spm": 0.9}}
    assert metric_quality(metrics, "knee_contact_deg") is None


def test_metric_quality_combina_confianca_e_cv():
    metrics = {
        "metric_confidence": {"knee_contact_deg": 0.8},
        "metric_cv": {"knee_contact_deg": 0.5},
    }
    # 0.8 * (1 - 0.5) = 0.4
    assert abs(metric_quality(metrics, "knee_contact_deg") - 0.4) < 1e-9


def test_metric_quality_sem_cv_usa_so_confianca():
    """Métrica de amostra única (ex. cadência) não tem CV entre passadas -> quality = confidence."""
    metrics = {"metric_confidence": {"cadence_spm": 0.85}}
    assert metric_quality(metrics, "cadence_spm") == 0.85


def test_metric_quality_cv_alto_e_clampado_em_1():
    metrics = {
        "metric_confidence": {"knee_contact_deg": 0.9},
        "metric_cv": {"knee_contact_deg": 5.0},   # CV absurdo -> min(cv,1.0) = 1.0
    }
    assert metric_quality(metrics, "knee_contact_deg") == 0.0


def test_diagnose_sem_metric_confidence_e_identico_ao_comportamento_anterior():
    """Regressão: sem metric_confidence, diagnose() se comporta EXATAMENTE como antes desta
    mudança (mesmo exemplo de tests/test_biomechanics.py)."""
    t = ideal_targets()
    metrics = {
        "cadence_spm": 150,
        "vertical_oscillation_pct": 9,
        "asymmetry_pct": 5,
        "trunk_lean_deg": 8,
    }
    devs = diagnose(metrics, t)
    metricas = [d["metric"] for d in devs]
    assert "asymmetry_pct" not in metricas and "trunk_lean_deg" not in metricas
    assert devs[0]["metric"] == "cadence_spm"
    assert devs[0]["side"] == "baixo"
    assert list(getattr(devs, "low_quality_metrics", [])) == []


def test_diagnose_qualidade_alta_entra_normalmente_em_deviations():
    t = ideal_targets()
    metrics = {
        "knee_contact_deg": 180,   # > 174 -> desvio
        "metric_confidence": {"knee_contact_deg": 0.95},
        "metric_cv": {"knee_contact_deg": 0.1},   # quality = 0.95*0.9 = 0.855 >= 0.6
    }
    devs = diagnose(metrics, t)
    assert any(d["metric"] == "knee_contact_deg" for d in devs)
    assert devs.low_quality_metrics == []


def test_diagnose_qualidade_baixa_e_suprimida_mas_fica_visivel():
    """Métrica que bateria a faixa de desvio, mas com quality < 0.6 (ex.: joelho por pose com
    MAE alto vs mocap) NAO entra em deviations — vira ruído clínico demais pra confiar — mas
    o valor medido continua acessível em low_quality_metrics."""
    t = ideal_targets()
    metrics = {
        "knee_contact_deg": 180,   # > 174 -> bateria desvio
        "metric_confidence": {"knee_contact_deg": 0.7},
        "metric_cv": {"knee_contact_deg": 0.5},   # quality = 0.7*0.5 = 0.35 < 0.6
    }
    devs = diagnose(metrics, t)
    assert all(d["metric"] != "knee_contact_deg" for d in devs)
    assert len(devs.low_quality_metrics) == 1
    lowq = devs.low_quality_metrics[0]
    assert lowq["metric"] == "knee_contact_deg"
    assert lowq["value"] == 180
    assert lowq["side"] == "alto"
    assert lowq["quality"] == 0.35


def test_diagnose_qualidade_baixa_nao_afeta_outras_metricas():
    """Uma métrica suprimida não deve tirar as outras (que têm quality boa ou sem info) de
    deviations."""
    t = ideal_targets()
    metrics = {
        "knee_contact_deg": 180,
        "cadence_spm": 150,   # sem info de qualidade -> comportamento normal
        "metric_confidence": {"knee_contact_deg": 0.5},
    }
    devs = diagnose(metrics, t)
    metricas = [d["metric"] for d in devs]
    assert "cadence_spm" in metricas
    assert "knee_contact_deg" not in metricas
    assert devs.low_quality_metrics[0]["metric"] == "knee_contact_deg"


def test_form_coach_plan_expoe_uncertain_metrics():
    """FormCoach.plan() propaga o que diagnose() suprimiu, pro frontend mostrar o selo de
    'medição incerta' — sem o LLM precisar comentar nada sobre isso."""
    llm = MagicMock()
    llm.chat.return_value = "- ajuste tal coisa por tal motivo, comece devagar (Fonte: PMC1)"
    coach = FormCoach(llm=llm, knowledge=None, risk_assessor=lambda *a, **k: {"score": 0.0, "by_injury": []})

    metrics = {
        "cadence_spm": 150,   # desvio normal, sem info de qualidade
        "knee_contact_deg": 180,
        "metric_confidence": {"knee_contact_deg": 0.4},
    }
    result = coach.plan(metrics)

    assert "uncertain_metrics" in result
    assert len(result["uncertain_metrics"]) == 1
    assert result["uncertain_metrics"][0]["metric"] == "knee_contact_deg"
    assert any(d["metric"] == "cadence_spm" for d in result["deviations"])
    assert all(d["metric"] != "knee_contact_deg" for d in result["deviations"])


def test_form_coach_plan_sem_supressao_uncertain_metrics_vazio():
    llm = MagicMock()
    llm.chat.return_value = "- ajuste tal coisa por tal motivo, comece devagar (Fonte: PMC1)"
    coach = FormCoach(llm=llm, knowledge=None, risk_assessor=lambda *a, **k: {"score": 0.0, "by_injury": []})
    result = coach.plan({"cadence_spm": 150})
    assert result["uncertain_metrics"] == []
