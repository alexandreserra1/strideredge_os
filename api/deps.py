"""api/deps.py — provedores de dependência (FastAPI Depends).

Centraliza a construção dos serviços. Nos testes, sobrescrevemos via
app.dependency_overrides para injetar fakes (ex: LLM falso) sem tocar o Ollama.
"""

from core.jobs import JobQueue, LocalJobQueue
from analytics.strength import StrengthSets
from analytics.form_coach import FormCoach
from api.auth import AuthService
from api.form import FormService
from api.profile import ProfileService
from api.services import ActivityService
from analytics.coach import Coach, OllamaClient
from analytics.fitness import RunningFitness
from analytics.sql_agent import SqlAgent
from analytics.training_load import TrainingLoad
from rag.knowledge_base import KnowledgeBase, OllamaEmbedder
from rag.rerank import LLMReranker, RerankedRetriever
from rag.web_search import WebSearchRetriever
from ingestion.strava_importer import StravaClient, StravaImporter


# SINGLETONS: a base e o reranker são reusados entre requests pra o CACHE do reranker
# persistir (senão cada request criaria um novo, com cache vazio). São stateless o bastante
# (o KB abre a conexao DuckDB por consulta; o reranker só guarda o cache em memória).
_KB = None
_RERANKER = None
_JOB_QUEUE = None


def get_job_queue() -> JobQueue:
    """Fila de jobs em background (singleton). Impl leve in-process hoje; troca por Celery
    na Fase F sem mexer em quem enfileira. Iniciada no startup da API (main.py)."""
    global _JOB_QUEUE
    if _JOB_QUEUE is None:
        _JOB_QUEUE = LocalJobQueue(workers=2)
    return _JOB_QUEUE


def _knowledge_base() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = KnowledgeBase(embedder=OllamaEmbedder())
    return _KB


def _reranked_knowledge():
    """Base de conhecimento com RAG híbrido + reranking pelo LLM local (sempre ligado — a
    qualidade extra vale a latência no coach corretivo, que não é streaming). Usado nas
    superfícies NÃO-streaming que toleram a chamada extra."""
    kb = _knowledge_base()
    global _RERANKER
    if _RERANKER is None:
        # Modelo PEQUENO dedicado ao rerank (so ordena indices — nao precisa do 7B). temp=0
        # (ordem deterministica) + num_predict baixo (a resposta e so "2,0,1,3") + keep_alive
        # longo (fica quente na memoria do Ollama, sem troca de modelo a cada chamada).
        rerank_llm = OllamaClient(model="qwen2.5:1.5b-instruct", temperature=0.0,
                                  num_predict=40, keep_alive="30m")
        _RERANKER = LLMReranker(rerank_llm)
    return RerankedRetriever(kb, _RERANKER, fetch_k=6)


def get_activity_service() -> ActivityService:
    return ActivityService()


def get_auth_service() -> AuthService:
    return AuthService()


def get_form_service() -> FormService:
    return FormService(queue=get_job_queue())


def get_strava_client() -> StravaClient:
    """Cliente da API do Strava (client_id/secret do ambiente). Um por request é barato."""
    return StravaClient()


def get_strava_importer() -> StravaImporter:
    """Importador do histórico do Strava (roda no worker da fila, não no request)."""
    return StravaImporter(client=get_strava_client())


def get_profile_service() -> ProfileService:
    return ProfileService()


def get_form_coach() -> FormCoach:
    """Algoritmo corretivo: alvos personalizados + exercícios citados (LLM local + RAG
    híbrido com reranking)."""
    return FormCoach(llm=OllamaClient(), knowledge=_reranked_knowledge())


def get_strength_sets() -> StrengthSets:
    return StrengthSets()


def get_training_load() -> TrainingLoad:
    return TrainingLoad()


def get_running_fitness() -> RunningFitness:
    return RunningFitness()


def get_sql_agent() -> SqlAgent:
    """Coach agêntico text-to-SQL (LLM gera SELECT; código valida e executa)."""
    return SqlAgent(llm=OllamaClient())


def build_coach(temperature: float = 0.2) -> Coach:
    """Monta o coach do VEREDITO. Usa RAG híbrido PURO (sem rerank) de propósito: o veredito
    tem endpoint em STREAMING, e a chamada extra do rerank atrasaria o primeiro token. O rerank
    fica no coach corretivo (não-streaming)."""
    return Coach(
        llm=OllamaClient(temperature=temperature),
        knowledge=_knowledge_base(),
        web=WebSearchRetriever(),
    )


def get_coach() -> Coach:
    """Coach completo para a API (sem params: FastAPI Depends nao injeta query)."""
    return build_coach()
