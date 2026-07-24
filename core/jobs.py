"""core/jobs.py — costura de execução de tarefas em BACKGROUND.

Um só padrão pra tudo que é lento e não pode bloquear a resposta HTTP: processar
vídeo (transcode + pose + métricas). O request só ENFILEIRA e responde na hora
("recebido"); um worker processa depois. O usuário pode fechar a página e voltar —
o status fica no banco.

Desenho (constituição §4 polimorfismo, §2 sem infra pesada até hospedar):
  - JobQueue (contrato) -> LocalJobQueue (impl leve, sem dependência: fila em
    memória + pool de threads). Quando hospedar (Fase F), uma CeleryJobQueue
    implementa a MESMA interface e a troca é de UMA linha no boot (deps.py) —
    o resto do código (quem enfileira) não muda. A API nunca sabe quem processa.
"""

import queue
import threading
from abc import ABC, abstractmethod
from typing import Callable

from core.logging import Logger

_log = Logger("jobs")


class JobQueue(ABC):
    """Contrato de uma fila de jobs. Quem enfileira não sabe (nem precisa saber)
    quem/como processa — só chama `enqueue`."""

    @abstractmethod
    def enqueue(self, fn: Callable, *args, **kwargs) -> bool:
        """Agenda `fn(*args, **kwargs)` e informa se a fila aceitou o trabalho."""

    @abstractmethod
    def start(self) -> None:
        """Sobe os workers (idempotente). Chamado uma vez no boot da API."""


class LocalJobQueue(JobQueue):
    """Fila em processo: `queue.Queue` + pool de N workers (threads daemon).

    `workers` limita a concorrência (backpressure): jobs além disso esperam na fila
    em vez de disparar processos sem teto. Modesto por padrão (2) pra não brigar no
    lock de escrita do DuckDB. Uma falha num job é logada e NÃO derruba o worker —
    o próximo job roda normal.
    """

    def __init__(self, workers: int = 2, max_pending: int = 8):
        self._q: "queue.Queue" = queue.Queue(maxsize=max_pending)
        self._workers = workers
        self._max_pending = max_pending
        self._threads: list = []
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self._workers):
            t = threading.Thread(target=self._run, name=f"job-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        _log.info("job_queue_started", workers=self._workers, max_pending=self._max_pending)

    def _run(self) -> None:
        while True:
            fn, args, kwargs = self._q.get()
            try:
                fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001 — um job ruim não pode derrubar o worker
                _log.error("job_failed", fn=getattr(fn, "__name__", str(fn)), error=str(e)[:200])
            finally:
                self._q.task_done()

    def enqueue(self, fn: Callable, *args, **kwargs) -> bool:
        """Não bloqueia o request quando a capacidade acabou: o controller pode devolver 503."""
        try:
            self._q.put_nowait((fn, args, kwargs))
            return True
        except queue.Full:
            _log.warning("job_queue_full", fn=getattr(fn, "__name__", str(fn)),
                         max_pending=self._max_pending)
            return False
