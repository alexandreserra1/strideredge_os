"""Coach modalidade-consciente: persona e analisadores mudam com o primary_type.

Treino de força NÃO pode ganhar conselho de passada/pace (bug real reportado).
"""

import pytest

from analytics.coach import Coach, DEFAULT_ANALYZERS
from analytics.run_analysis import (
    BreakingPointAnalyzer, CadenceReferenceAnalyzer, DurabilityAnalyzer,
    EfficiencyAnalyzer, TerrainContextAnalyzer,
)
from core.database import get_connection
from core.framework.interfaces import BaseLLMClient

STRENGTH_ID = "44444444-4444-4444-4444-444444444444"
RUN_ANALYZERS = (BreakingPointAnalyzer, EfficiencyAnalyzer, TerrainContextAnalyzer,
                 CadenceReferenceAnalyzer, DurabilityAnalyzer)


class CapturingLLM(BaseLLMClient):
    """Guarda o system prompt recebido — prova qual persona foi usada."""

    def __init__(self):
        self.last_system = None

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system = system_prompt
        return "VEREDITO_FAKE"


@pytest.fixture
def strength_activity():
    con = get_connection()
    con.execute(
        """INSERT INTO dim_activities
           (activity_id, garmin_activity_id, activity_name, start_time,
            total_distance_meters, total_duration_seconds, primary_type)
           VALUES (?, 999, 'Franco Força A', '2026-06-20 07:00:00', 0, 2400, 'STRENGTH')""",
        [STRENGTH_ID])
    yield STRENGTH_ID
    con.execute("DELETE FROM cache_coach_verdicts WHERE activity_id = ?", [STRENGTH_ID])
    con.execute("DELETE FROM dim_activities WHERE activity_id = ?", [STRENGTH_ID])


def test_analisadores_de_corrida_ficam_fora_da_forca():
    coach = Coach(llm=CapturingLLM())
    strength = coach.analyzers_for("STRENGTH")
    assert not any(isinstance(a, RUN_ANALYZERS) for a in strength)
    # corrida mantém a lista completa
    assert len(coach.analyzers_for("RUN")) == len(DEFAULT_ANALYZERS)


def test_persona_por_modalidade():
    coach = Coach(llm=CapturingLLM())
    assert "FORCA" in coach.system_prompt("STRENGTH").upper()
    assert "NAO fale de passada" in coach.system_prompt("STRENGTH")
    assert "CORRIDA" in coach.system_prompt("RUN").upper()
    assert coach.system_prompt("HYROX") == coach.system_prompt("HIIT")
    assert coach.system_prompt("TIPO_DESCONHECIDO") == coach.system_prompt("RUN")   # fallback


def test_verdito_de_forca_usa_persona_de_forca(strength_activity):
    llm = CapturingLLM()
    coach = Coach(llm=llm)
    prompt = coach.build_user_prompt(strength_activity)
    assert "cadencia de referencia" not in prompt.lower()   # análise de corrida não entra
    coach.verdict(strength_activity)
    assert "treinador de FORCA" in llm.last_system
    assert "cadencia" in llm.last_system.lower()            # a proibição está lá


def test_header_de_forca_sem_cadencia(strength_activity):
    coach = Coach(llm=CapturingLLM())
    header = coach._header(strength_activity)
    assert "Cadencia media" not in header                   # cadência só em corrida
    assert "FC media" in header
