"""api/deps.py — provedores de dependência (FastAPI Depends).

Centraliza a construção dos serviços. Nos testes, sobrescrevemos via
app.dependency_overrides para injetar fakes (ex: LLM falso) sem tocar o Ollama.
"""

from core.jobs import JobQueue, LocalJobQueue
from analytics.form_coach import FormCoach
from analytics.llm import OllamaClient
from api.auth import AuthService
from api.form import FormService
from api.injuries import InjuryService
from api.profile import ProfileService
from rag.knowledge_base import KnowledgeBase, OllamaEmbedder


# SINGLETON: a base é reusada entre requests (o KB abre a conexao DuckDB por consulta,
# então é stateless o bastante). O reranking foi REMOVIDO: o eval (analytics/rag_eval)
# mostrou que num corpus curado a busca híbrida densa+BM25 já acerta 10/10 no top-2, e o
# reranker pelo LLM pequeno DEGRADAVA a recuperação (10→7). Ver AI-STRATEGY.md.
_KB = None
_JOB_QUEUE = None


def get_job_queue() -> JobQueue:
    """Fila de jobs em background (singleton). Impl leve in-process hoje; troca por Celery
    quando hospedar sem mexer em quem enfileira. Iniciada no startup da API (main.py)."""
    global _JOB_QUEUE
    if _JOB_QUEUE is None:
        _JOB_QUEUE = LocalJobQueue(workers=2)
    return _JOB_QUEUE


def _knowledge_base() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = KnowledgeBase(embedder=OllamaEmbedder())
    return _KB


def get_auth_service() -> AuthService:
    return AuthService()


def get_form_service() -> FormService:
    return FormService(queue=get_job_queue())


def get_profile_service() -> ProfileService:
    return ProfileService()


def get_injury_service() -> InjuryService:
    return InjuryService()


def get_plan_service():
    """Persistência dos planos corretivos gerados."""
    from api.plans import PlanService
    return PlanService()


def get_diagnosis_classifier():
    """Classificador texto→diagnóstico (LLM local, conjunto fechado + abstenção)."""
    from analytics.injury_classifier import DiagnosisClassifier
    return DiagnosisClassifier(llm=OllamaClient())


def get_form_coach() -> FormCoach:
    """Algoritmo corretivo: alvos personalizados + exercícios citados (LLM local + RAG
    híbrido denso+BM25). Risco: modelo TREINADO se há dado real suficiente, senão o prior."""
    from analytics.risk_assessor import current_assessor
    return FormCoach(llm=OllamaClient(), knowledge=_knowledge_base(),
                     risk_assessor=current_assessor())
