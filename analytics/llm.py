"""analytics/llm.py — cliente do LLM local (Ollama).

OllamaClient implementa BaseLLMClient (polimorfismo: trocar o "cérebro" sem mexer em
quem usa). Servido pelo Ollama, 100% local, sem token. Usado pelo FormCoach (plano
corretivo), pelo ContextGenerator (indexação) e pelo LLM-judge dos evals.

`chat` é bloqueante (espera o texto inteiro) — bom pro grounding/eval, que validam a resposta
fechada. `chat_stream` (A3) devolve os tokens conforme saem: o /coach entrega o bloco
determinístico na hora e transmite a explicação por cima, sem o atleta esperar a geração inteira.
Teto de tokens (`num_predict`) e keep_alive já cortam a latência da parte que bloqueia.
"""

import json
import os
from typing import Iterator, Optional

import httpx

from core.framework.interfaces import BaseLLMClient

# Modelo do coach: trocável por env (STRIDE_LLM_MODEL) SEM tocar em código — é o ponto do contrato
# BaseLLMClient. Qualquer modelo servido pelo Ollama local vale (inclusive um GGUF importado do
# Hugging Face via `ollama create`). Default = o validado hoje.
_DEFAULT_LLM_MODEL = "qwen2.5:7b-instruct"

# Client HTTP reusado entre chamadas: evita reabrir conexao TCP a cada request ao Ollama
# (handshake tem custo perceptivel quando a chamada em si dura poucos segundos, como no rerank).
_HTTP = httpx.Client(timeout=120.0)


class OllamaClient(BaseLLMClient):
    """Cliente do LLM local servido pelo Ollama (implementa BaseLLMClient)."""

    def __init__(self, model: Optional[str] = None,
                 url: str = "http://localhost:11434/api/chat", temperature: float = 0.2,
                 num_predict: int = -1, keep_alive: str = "30m"):
        # sem argumento explícito, usa STRIDE_LLM_MODEL do ambiente; senão, o default validado.
        self.model = model or os.getenv("STRIDE_LLM_MODEL", _DEFAULT_LLM_MODEL)
        self.url = url
        self.temperature = temperature   # baixa = mais factual; 0 = deterministico (eval)
        self.num_predict = num_predict   # teto de tokens de saida (-1 = sem teto)
        self.keep_alive = keep_alive     # mantem o modelo "quente" na memoria do Ollama

    def _payload(self, system_prompt: str, user_prompt: str, stream: bool = False) -> dict:
        options = {"temperature": self.temperature}
        if self.num_predict > 0:
            options["num_predict"] = self.num_predict
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": stream,
            "keep_alive": self.keep_alive,
            "options": options,
        }

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        response = _HTTP.post(self.url, json=self._payload(system_prompt, user_prompt))
        response.raise_for_status()
        return response.json()["message"]["content"]

    def chat_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Gera os pedaços de texto conforme o Ollama emite (NDJSON, um objeto por linha).
        Encerra quando `done`. Permite o /coach mostrar os primeiros tokens sem esperar o fim."""
        payload = self._payload(system_prompt, user_prompt, stream=True)
        with _HTTP.stream("POST", self.url, json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                chunk, done = _content_from_line(line)
                if chunk:
                    yield chunk
                if done:
                    break


def _content_from_line(line: str) -> tuple:
    """Uma linha NDJSON do Ollama → (pedaço_de_texto, terminou?). Ignora linha vazia/inválida.
    Puro (sem rede) — testável isolado. O texto vive em message.content; o fim em done=true."""
    if not line or not line.strip():
        return None, False
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        return None, False
    return (obj.get("message") or {}).get("content"), bool(obj.get("done"))
