"""api/deps.py — provedores de dependência (FastAPI Depends).

Centraliza a construção dos serviços. Nos testes, sobrescrevemos via
app.dependency_overrides para injetar fakes (ex: LLM falso) sem tocar o Ollama.
"""

from api.services import ActivityService
from analytics.coach import Coach, OllamaClient
from analytics.sql_agent import SqlAgent
from analytics.training_load import TrainingLoad
from rag.knowledge_base import KnowledgeBase, OllamaEmbedder
from rag.web_search import WebSearchRetriever


def get_activity_service() -> ActivityService:
    return ActivityService()


def get_training_load() -> TrainingLoad:
    return TrainingLoad()


def get_sql_agent() -> SqlAgent:
    """Coach agêntico text-to-SQL (LLM gera SELECT; código valida e executa)."""
    return SqlAgent(llm=OllamaClient())


def get_coach() -> Coach:
    """Coach completo: LLM local + base curada (RAG) + fallback de web."""
    return Coach(
        llm=OllamaClient(),
        knowledge=KnowledgeBase(embedder=OllamaEmbedder()),
        web=WebSearchRetriever(),
    )
