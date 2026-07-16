"""core/logging.py — logging estruturado (classe Logger sobre structlog).

Substitui prints ad-hoc dos caminhos OPERACIONAIS (sync, ingestão, API) por logs
estruturados (uma linha JSON por evento). Os prints de CLI (__main__) ficam como
são — são UX de terminal.

Uso (importa a classe no lugar do print):
    from core.logging import Logger
    log = Logger("form")
    log.info("form_done", analysis_id="abc", status="done")
    log = log.bind(trace_id="abc123")   # contexto que acompanha os eventos
"""

import logging

import structlog

from core.database import PROJECT_ROOT

LOG_FILE = PROJECT_ROOT / "storage" / "strideredge.log"


class Logger:
    """Logger estruturado (JSON em arquivo). Wrapper OOP do structlog."""

    _configured = False

    def __init__(self, name: str = None):
        Logger._configure()
        self._log = structlog.get_logger(name)

    @classmethod
    def _configure(cls) -> None:
        if cls._configured:
            return
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            logger_factory=structlog.PrintLoggerFactory(file=open(LOG_FILE, "a", encoding="utf-8")),
            cache_logger_on_first_use=False,  # False p/ capture_logs funcionar nos testes
        )
        cls._configured = True

    def bind(self, **context) -> "Logger":
        """Devolve um Logger com contexto fixo (ex: trace_id) em todos os eventos."""
        new = Logger.__new__(Logger)
        new._log = self._log.bind(**context)
        return new

    def info(self, event: str, **kw) -> None:
        self._log.info(event, **kw)

    def warning(self, event: str, **kw) -> None:
        self._log.warning(event, **kw)

    def error(self, event: str, **kw) -> None:
        self._log.error(event, **kw)
