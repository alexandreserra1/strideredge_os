"""analytics/llm.py — cliente do LLM local (Ollama).

OllamaClient implementa BaseLLMClient (polimorfismo: trocar o "cérebro" sem mexer em
quem usa). Servido pelo Ollama, 100% local, sem token. Usado pelo FormCoach (plano
corretivo), pelo ContextGenerator (indexação) e pelo LLM-judge dos evals.
"""

import httpx

from core.framework.interfaces import BaseLLMClient

# Client HTTP reusado entre chamadas: evita reabrir conexao TCP a cada request ao Ollama
# (handshake tem custo perceptivel quando a chamada em si dura poucos segundos, como no rerank).
_HTTP = httpx.Client(timeout=120.0)


class OllamaClient(BaseLLMClient):
    """Cliente do LLM local servido pelo Ollama (implementa BaseLLMClient)."""

    def __init__(self, model: str = "qwen2.5:7b-instruct",
                 url: str = "http://localhost:11434/api/chat", temperature: float = 0.2,
                 num_predict: int = -1, keep_alive: str = "30m"):
        self.model = model
        self.url = url
        self.temperature = temperature   # baixa = mais factual; 0 = deterministico (eval)
        self.num_predict = num_predict   # teto de tokens de saida (-1 = sem teto)
        self.keep_alive = keep_alive     # mantem o modelo "quente" na memoria do Ollama

    def _payload(self, system_prompt: str, user_prompt: str) -> dict:
        options = {"temperature": self.temperature}
        if self.num_predict > 0:
            options["num_predict"] = self.num_predict
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": options,
        }

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        response = _HTTP.post(self.url, json=self._payload(system_prompt, user_prompt))
        response.raise_for_status()
        return response.json()["message"]["content"]
