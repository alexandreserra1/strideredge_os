"""Consistência da taxonomia de lesão + biblioteca de exercícios (herméticos, sem rede)."""

from analytics.biomechanics import ideal_targets
from analytics.injury_taxonomy import (
    DIAGNOSES, REGIONS, valid_diagnosis, is_mapped, factors_for, diagnoses_for_region,
)
from analytics.exercises import EXERCISES, PHASES, for_factors

_VALID_KEYS = set(ideal_targets().keys())


def test_todo_factor_referencia_chave_real_de_biomechanics():
    """O mapa lesão↔fator só pode usar chaves que o motor mede (fonte única)."""
    for dx, d in DIAGNOSES.items():
        for f in d["factors"]:
            assert f in _VALID_KEYS, f"{dx}: fator '{f}' não existe em ideal_targets"


def test_lesao_mapeada_tem_fonte_e_fatores():
    for dx in DIAGNOSES:
        if is_mapped(dx):
            assert DIAGNOSES[dx]["source"] and factors_for(dx), f"{dx} mapeada mas sem fonte/fatores"
        else:
            # não-mapeada (ex.: plantar/aquiles) — sem fonte, sem fatores, mas entra no log
            assert DIAGNOSES[dx]["source"] is None and factors_for(dx) == []


def test_regiao_de_toda_lesao_e_valida():
    for d in DIAGNOSES.values():
        assert d["region"] in REGIONS


def test_helpers_diagnostico():
    assert valid_diagnosis("pfp") and not valid_diagnosis("inexistente")
    assert "pfp" in diagnoses_for_region("joelho_frente")
    assert is_mapped("plantar") and "cadence_spm" in factors_for("plantar")  # mapeada (proxy de carga)


def test_exercicios_citados_e_com_fase_valida():
    for e in EXERCISES:
        assert e["source"] and e["phase"] in PHASES
        for f in e["targets"]:
            assert f in _VALID_KEYS, f"exercício {e['id']}: alvo '{f}' inválido"


def test_for_factors_casa_por_alvo():
    ex = for_factors(["pelvic_drop_deg"])
    ids = {e["id"] for e in ex}
    assert "band_walk" in ids and "hip_abd_strength" in ids
    assert for_factors(["metrica_inexistente"]) == []
