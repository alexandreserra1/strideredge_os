"""core/framework/interfaces.py — contratos abstratos (OOP framework).

Define O QUE cada componente deve fazer, sem dizer COMO. Implementacoes
concretas herdam destas classes. Isso mantem o sistema extensivel: novos
formatos de arquivo ou novos modelos preditivos so precisam cumprir o contrato.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional

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

    def chat_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Gera em STREAMING (tokens conforme nascem). Padrao: a resposta inteira num
        unico chunk — provedores com suporte real (Ollama) sobrescrevem. Assim fakes de
        teste e clientes antigos funcionam sem mudar nada."""
        yield self.chat(system_prompt, user_prompt)


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


class BaseGuard(ABC):
    """Contrato para uma GUARDA de qualidade sobre a saida do LLM (ex: aterramento).

    POLIMORFISMO: trocar a politica (mais/menos rigida, ou outra dimensao) sem mexer no
    Coach, que apenas COMPOE uma guarda e chama enforce(). Padrao template-method: a base
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


class BaseCueRule(ABC):
    """Regra de coaching em TEMPO REAL (Strategy). Olha a janela recente + o alvo e talvez
    devolve a mensagem de um aviso. O cooldown (nao repetir o mesmo aviso a cada tick) e
    tratado aqui (template-method); a subclasse so implementa _check (a condicao).

    POLIMORFISMO: adicionar uma regra nova = nova subclasse, sem mexer no motor (RealtimeCoach).
    """

    kind: str = "cue"          # categoria do aviso ("pace", "hr", "cadence")
    priority: int = 1          # seguranca (FC) > pace > cadencia
    sustain_s: float = 8.0     # o problema precisa PERSISTIR isso antes de avisar (ignora blip)
    cooldown_s: float = 180.0  # re-lembrete do MESMO problema so apos isso (evita tagarelar)

    def __init__(self):
        self._pending_msg: Optional[str] = None    # problema observado agora (ainda nao falado)
        self._pending_since: Optional[float] = None
        self._spoken_msg: Optional[str] = None      # ultimo problema FALADO
        self._last_fire: Optional[float] = None

    @abstractmethod
    def _check(self, window: Any, target: Any) -> Optional[str]:
        """Devolve a MENSAGEM do aviso se a condicao bate; senao None (tudo certo)."""
        ...

    def evaluate(self, window: Any, target: Any, now: float) -> Optional[str]:
        """Fala como gente: so avisa se o problema (a) PERSISTIU (sustain), e (b) e NOVO vs. o
        ultimo falado OU ja passou o cooldown de re-lembrete. Devolve a mensagem ou None."""
        msg = self._check(window, target)
        if msg is None:                       # voltou ao normal: zera (proximo problema fala de novo)
            self._pending_msg = self._pending_since = self._spoken_msg = None
            return None
        if msg != self._pending_msg:          # problema novo/mudou -> reinicia o relogio de sustentacao
            self._pending_msg, self._pending_since = msg, now
        if now - self._pending_since < self.sustain_s:
            return None                        # ainda nao persistiu o bastante
        new_problem = msg != self._spoken_msg
        cooldown_ok = self._last_fire is None or now - self._last_fire >= self.cooldown_s
        if new_problem or cooldown_ok:
            self._spoken_msg, self._last_fire = msg, now
            return msg
        return None


class BaseAnnouncer(ABC):
    """Entrega um aviso ao atleta. POLIMORFISMO: trocar o canal (voz no Mac, TTS do celular,
    log silencioso nos testes) sem mexer no motor."""

    @abstractmethod
    def announce(self, cue: Any) -> None:
        """Fala/registra o Cue."""
        ...


class BaseAnalyzer(ABC):
    """Contrato para uma analise de UM treino (ponto de quebra, eficiencia, zonas...).

    Permite ao Coach reunir metricas de varios analisadores de forma POLIMORFICA:
    adicionar uma analise nova = criar uma subclasse, sem mexer no Coach
    (principio aberto/fechado).
    """

    label: str = "analise"   # nome legivel da analise
    # Modalidades onde a analise faz sentido (None = todas). Analises de corrida
    # (pace/cadencia/terreno) marcam {"RUN"} — treino de forca nao ganha conselho de passada.
    types = None

    @abstractmethod
    def analyze(self, activity_id: str) -> dict:
        """Calcula a metrica e devolve o resultado bruto (dict)."""
        ...

    @abstractmethod
    def to_prompt(self, result: dict) -> Optional[str]:
        """Resume o resultado numa linha para o prompt do LLM (ou None se nada relevante)."""
        ...
