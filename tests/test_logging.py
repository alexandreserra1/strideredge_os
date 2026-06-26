"""Teste da classe Logger — captura eventos sem escrever em disco."""

from structlog.testing import capture_logs

from core.logging import Logger


def test_logger_emits_structured_event():
    log = Logger("teste")
    with capture_logs() as logs:
        log.info("treino_importado", garmin_id=42, status="imported")
    evt = next(e for e in logs if e["event"] == "treino_importado")
    assert evt["garmin_id"] == 42 and evt["status"] == "imported"


def test_logger_binds_context():
    log = Logger("teste").bind(trace_id="abc123")
    with capture_logs() as logs:
        log.info("evento")
    assert logs[0]["trace_id"] == "abc123"
