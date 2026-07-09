"""Repositório de telemetria — a fronteira de acesso a dado compartilhada."""

import pytest

from core.repository import TelemetryRepository

FLORIPA_ID = "22222222-2222-2222-2222-222222222222"   # semeada no conftest (com GPS)


def test_series_ordenada_e_filtro_non_null():
    repo = TelemetryRepository()
    rows = repo.series(FLORIPA_ID, ["latitude", "longitude"], non_null="latitude")
    assert rows and all(r[0] is not None for r in rows)   # nenhum NULL passou
    # ordenada por timestamp: latitude decresce monotonicamente no seed
    lats = [r[0] for r in rows]
    assert lats == sorted(lats, reverse=True)


def test_column_devolve_floats():
    vals = TelemetryRepository().column(FLORIPA_ID, "cadence")
    assert vals and all(isinstance(v, float) for v in vals)


def test_coluna_desconhecida_e_rejeitada():
    # defesa: nome de coluna arbitrário nunca vira SQL
    with pytest.raises(ValueError):
        TelemetryRepository().series(FLORIPA_ID, ["latitude; DROP TABLE"], non_null=None)
    with pytest.raises(ValueError):
        TelemetryRepository().series(FLORIPA_ID, ["heart_rate"], non_null="inexistente")
