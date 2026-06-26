"""Testes das métricas de eval anti-alucinação (determinísticas, sem LLM).

As métricas medem se o veredito é FIEL ao que demos: números e citações no
veredito têm que aparecer no prompt (dados + evidências).
"""

import httpx
import pytest

from analytics.coach_eval import CoachEvaluator

ev = CoachEvaluator(coach=None)  # as métricas não usam o coach


def _ollama_up() -> bool:
    try:
        httpx.get("http://localhost:11434/api/version", timeout=2.0)
        return True
    except Exception:
        return False


def test_numeric_fidelity_perfect():
    assert ev.numeric_fidelity("cadência 162 e FC 154", "162 spm ... 154 bpm") == 1.0


def test_numeric_fidelity_flags_invented_number():
    # 200 não está no prompt -> 1 de 2 suportado
    assert ev.numeric_fidelity("162 e 200", "só 162 aqui") == 0.5


def test_numeric_fidelity_no_numbers_is_one():
    assert ev.numeric_fidelity("texto sem números", "qualquer") == 1.0


def test_citation_validity_valid():
    assert ev.citation_validity("ver PMC12440572", "evidência PMC12440572") == 1.0


def test_citation_validity_flags_fake_source():
    assert ev.citation_validity("ver PMC99999", "evidência PMC12440572") == 0.0


def test_citation_validity_no_citation_is_one():
    assert ev.citation_validity("sem citação", "x") == 1.0


@pytest.mark.skipif(not _ollama_up(), reason="Ollama não está rodando")
def test_real_coach_stays_grounded():
    """Guarda de regressão: o coach real não pode começar a alucinar."""
    from analytics.coach import Coach, OllamaClient
    from rag.knowledge_base import KnowledgeBase, OllamaEmbedder
    from core.database import get_connection

    aid = str(get_connection().execute(
        "SELECT activity_id FROM dim_activities WHERE activity_name = 'Corrida Floripa'"
    ).fetchone()[0])
    coach = Coach(llm=OllamaClient(), knowledge=KnowledgeBase(embedder=OllamaEmbedder()))
    r = CoachEvaluator(coach).evaluate(aid)
    assert r["citation_validity"] >= 0.8, f"citações inválidas: {r['citation_validity']}"
    assert r["numeric_fidelity"] >= 0.7, f"números inventados demais: {r['numeric_fidelity']}"
