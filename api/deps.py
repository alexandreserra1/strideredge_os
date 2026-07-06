"""api/deps.py — provedores de dependência (FastAPI Depends).

Centraliza a construção dos serviços. Nos testes, sobrescrevemos via
app.dependency_overrides para injetar fakes (ex: LLM falso) sem tocar o Ollama.
"""

from api.auth import AuthService
from api.services import ActivityService
from analytics.coach import Coach, OllamaClient
from analytics.fitness import RunningFitness
from analytics.sql_agent import SqlAgent
from analytics.training_load import TrainingLoad
from rag.knowledge_base import KnowledgeBase, OllamaEmbedder
from rag.web_search import WebSearchRetriever


def get_activity_service() -> ActivityService:
    return ActivityService()


def get_auth_service() -> AuthService:
    return AuthService()


def get_training_load() -> TrainingLoad:
    return TrainingLoad()


def get_running_fitness() -> RunningFitness:
    return RunningFitness()


def get_sql_agent() -> SqlAgent:
    """Coach agêntico text-to-SQL (LLM gera SELECT; código valida e executa)."""
    return SqlAgent(llm=OllamaClient())


def build_coach(temperature: float = 0.2) -> Coach:
    """Monta o coach completo (LLM local + RAG + fallback web). temperature=0 -> eval deterministico."""
    return Coach(
        llm=OllamaClient(temperature=temperature),
        knowledge=KnowledgeBase(embedder=OllamaEmbedder()),
        web=WebSearchRetriever(),
    )


def get_coach() -> Coach:
    """Coach completo para a API (sem params: FastAPI Depends nao injeta query)."""
    return build_coach()
