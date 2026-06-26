"""core/framework/interfaces.py — contratos abstratos (OOP framework).

Define O QUE cada componente deve fazer, sem dizer COMO. Implementacoes
concretas herdam destas classes. Isso mantem o sistema extensivel: novos
formatos de arquivo ou novos modelos preditivos so precisam cumprir o contrato.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import polars as pl


class BaseTelemetryParser(ABC):
    """Contrato para extrair telemetria de um arquivo bruto.

    Para suportar .GPX, .TCX ou sensores IoT no futuro, basta criar uma nova
    classe que herde desta e implemente os dois metodos abstratos.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    @abstractmethod
    def validate_file(self) -> bool:
        """Valida integridade estrutural e headers do arquivo bruto."""
        ...

    @abstractmethod
    def to_dataframe(self) -> pl.DataFrame:
        """Extrai os registros e devolve um DataFrame Polars padronizado."""
        ...


class BasePredictiveEngine(ABC):
    """Contrato para motores de ML / analise estatistica temporal."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = self._load_model()

    @abstractmethod
    def _load_model(self) -> Any:
        """Carrega o artefato binario do modelo treinado."""
        ...

    @abstractmethod
    def predict_anomalies(self, data: pl.DataFrame) -> List[Dict[str, Any]]:
        """Procura anomalias mecanicas no DataFrame de telemetria."""
        ...


class BaseIntelligenceNotifier(ABC):
    """Contrato para envio dos relatorios gerados pela IA (Coach Sintetico)."""

    @abstractmethod
    def dispatch_report(self, user_id: str, payload: Dict[str, Any]) -> bool:
        """Envia os insights consolidados ao destino final (terminal, etc)."""
        ...


class BaseLLMClient(ABC):
    """Contrato para um modelo de linguagem (o "cerebro" que gera texto).

    Permite POLIMORFISMO: trocar o modelo (Ollama local, Claude, etc.) sem mudar
    quem usa. Cada provedor e uma subclasse que implementa `chat`.
    """

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Recebe persona (system) + dados (user) e devolve a resposta gerada."""
        ...


class BaseEmbedder(ABC):
    """Contrato para transformar texto em vetor (embedding) para busca semantica.

    POLIMORFISMO: trocar o modelo de embedding (nomic local, outro) sem mexer em
    quem usa. Textos com sentido parecido viram vetores proximos.
    """

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Converte um texto num vetor de numeros (lista de floats)."""
        ...

    # Documento e pergunta podem precisar de tratamento diferente (ex: prefixos
    # de tarefa em alguns modelos). Por padrao sao iguais; o embedder sobrescreve.
    def embed_document(self, text: str) -> List[float]:
        return self.embed(text)

    def embed_query(self, text: str) -> List[float]:
        return self.embed(text)


class BaseRetriever(ABC):
    """Contrato para recuperar trechos relevantes para uma pergunta (RAG).

    POLIMORFISMO: base curada (DuckDB) e busca na web sao intercambiaveis. Cada
    uma devolve a mesma forma: lista de {text, source, origin}.
    """

    @abstractmethod
    def retrieve(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Devolve ate k trechos relevantes: [{text, source, origin}]."""
        ...


class BaseAnalyzer(ABC):
    """Contrato para uma analise de UM treino (ponto de quebra, eficiencia, zonas...).

    Permite ao Coach reunir metricas de varios analisadores de forma POLIMORFICA:
    adicionar uma analise nova = criar uma subclasse, sem mexer no Coach
    (principio aberto/fechado).
    """

    label: str = "analise"   # nome legivel da analise

    @abstractmethod
    def analyze(self, activity_id: str) -> dict:
        """Calcula a metrica e devolve o resultado bruto (dict)."""
        ...

    @abstractmethod
    def to_prompt(self, result: dict) -> Optional[str]:
        """Resume o resultado numa linha para o prompt do LLM (ou None se nada relevante)."""
        ...
