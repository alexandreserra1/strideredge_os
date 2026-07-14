"""core/framework/interfaces.py — contratos abstratos (OOP framework).

Define O QUE cada componente deve fazer, sem dizer COMO. Implementacoes concretas herdam
destas classes → polimorfismo: trocar a implementacao sem mexer no resto. Os 4 contratos do
nucleo de IA de forma: LLM (cerebro), Embedder (texto→vetor), Retriever (RAG) e Guard (guarda
de aterramento anti-alucinacao).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional


class BaseLLMClient(ABC):
    """Contrato para um modelo de linguagem (o "cerebro" que gera texto).

    Permite POLIMORFISMO: trocar o modelo (Ollama local, Claude, etc.) sem mudar
    quem usa. Cada provedor e uma subclasse que implementa `chat`.
    """

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Recebe persona (system) + dados (user) e devolve a resposta gerada."""
        ...

    def chat_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Gera em STREAMING (tokens conforme nascem). Padrao: a resposta inteira num
        unico chunk — provedores com suporte real (Ollama) sobrescrevem. Assim fakes de
        teste e clientes antigos funcionam sem mudar nada."""
        yield self.chat(system_prompt, user_prompt)


class BaseEmbedder(ABC):
    """Contrato para transformar texto em vetor (embedding) para busca semantica.

    POLIMORFISMO: trocar o modelo de embedding (bge-m3 local, outro) sem mexer em
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


class BaseGuard(ABC):
    """Contrato para uma GUARDA de qualidade sobre a saida do LLM (ex: aterramento).

    POLIMORFISMO: trocar a politica (mais/menos rigida, ou outra dimensao) sem mexer em
    quem usa, que apenas COMPOE uma guarda e chama enforce(). Padrao template-method: a base
    define o loop de regeneracao; a subclasse define O QUE e problema (issues) e COMO
    corrigir (_correction).
    """

    @abstractmethod
    def issues(self, output: str, reference: str) -> Dict[str, list]:
        """Problemas da 'output' frente ao texto de 'reference' (dict de listas; vazio = ok)."""
        ...

    def is_clean(self, output: str, reference: str) -> bool:
        return not any(self.issues(output, reference).values())

    def enforce(self, llm: "BaseLLMClient", system_prompt: str, user_prompt: str,
                max_retries: int = 2, first: Optional[str] = None) -> str:
        """Gera com o LLM e REGENERA enquanto houver problema (ate max_retries). Devolve a
        melhor tentativa (menos problemas) — enforcement em codigo, sem confiar so no modelo.

        `first` = saida ja gerada fora daqui (ex: streaming): vira a tentativa 0 sem
        chamar o LLM de novo; o loop de correcao continua identico a partir dela."""
        best, best_score, prompt = None, None, user_prompt
        for attempt in range(max_retries + 1):
            out = first if attempt == 0 and first is not None else llm.chat(system_prompt, prompt)
            found = self.issues(out, user_prompt)
            score = sum(len(v) for v in found.values())
            if best_score is None or score < best_score:
                best, best_score = out, score
            if score == 0:
                break
            prompt = user_prompt + "\n\n" + self._correction(found)
        return best

    def _correction(self, issues: Dict[str, list]) -> str:
        """Mensagem de correcao para a regeneracao (subclasse sobrescreve)."""
        return "CORRECAO: ajuste a resposta para remover os problemas detectados."
