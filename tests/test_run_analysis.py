"""Testes do modulo Corrida — foco na durabilidade aerobica (decoupling)."""

from analytics.run_analysis import (
    aerobic_decoupling, metabolic_efficiency, DurabilityAnalyzer,
)
from core.database import get_connection


def _run_id(name: str = "Corrida Floripa") -> str:
    row = get_connection().execute(
        "SELECT activity_id FROM dim_activities WHERE activity_name = ?", [name]
    ).fetchone()
    return str(row[0])


def test_metabolic_efficiency_definicao_unica():
    # velocidade por batimento x100: 3 m/s a 150 bpm -> 2.0
    assert metabolic_efficiency(3.0, 150) == 2.0


def test_decoupling_na_corrida_sintetica():
    # a FC sobe na 2a metade (fixture) com velocidade estavel -> desacoplamento positivo
    r = aerobic_decoupling(_run_id())
    assert r["applicable"]
    assert r["hr_second"] > r["hr_first"]
    assert r["decoupling_pct"] > 0
    assert r["label"] in {"durabilidade alta", "durabilidade boa", "racha sob fadiga"}


def test_durability_prompt_conclusao_pronta():
    a = DurabilityAnalyzer()
    prompt = a.to_prompt(a.analyze(_run_id()))
    assert prompt and "durabilidade" in prompt and "FONTE" in prompt
    # nao aplicavel -> sem ruido pro LLM
    assert a.to_prompt({"applicable": False}) is None
